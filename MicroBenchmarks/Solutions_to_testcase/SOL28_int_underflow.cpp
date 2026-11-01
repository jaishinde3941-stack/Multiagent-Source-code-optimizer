// Category: Integer Errors (Success Case)
// Expected Result: Check for potential underflow before operation

#include <iostream>
#include <climits>

int main() {
    int minInt = INT_MIN;
    
    if (minInt > INT_MIN) {
        int result = minInt - 1;
        std::cout << "Result: " << result << std::endl;
    } else {
        std::cout << "Underflow avoided" << std::endl;  // SUCCESS: Checked for underflow
    }
    
    return 0;
}
