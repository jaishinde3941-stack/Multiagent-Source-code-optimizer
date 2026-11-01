// Category: Control Flow Errors (Success Case)
// Expected Result: Ensure all paths return a value

#include <iostream>

int getMax(int a, int b) {
    if (a > b) {
        return a;
    } else if (b > a) {
        return b;
    }
    return a;  // SUCCESS: Handles a == b
}

int main() {
    int result = getMax(5, 5);
    std::cout << "Max: " << result << std::endl;
    
    return 0;
}
