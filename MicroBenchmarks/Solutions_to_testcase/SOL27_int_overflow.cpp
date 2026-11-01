// Category: Integer Errors (Success Case)
// Expected Result: Check for potential overflow before operation

#include <iostream>
#include <climits>

int main() {
    int maxInt = INT_MAX;
    
    if (maxInt < INT_MAX) {
        int result = maxInt + 1;
        std::cout << "Result: " << result << std::endl;
    } else {
        std::cout << "Overflow avoided" << std::endl;  // SUCCESS: Checked for overflow
    }
    
    return 0;
}
