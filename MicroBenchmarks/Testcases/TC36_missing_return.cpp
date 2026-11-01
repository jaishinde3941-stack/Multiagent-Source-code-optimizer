// Category: Control Flow Errors
// Error: Missing return statement

#include <iostream>

int getMax(int a, int b) {
    if (a > b) {
        return a;
    } else if (b > a) {
        return b;
    }
    // ERROR: Missing return when a == b
}

int main() {
    int result = getMax(5, 5);
    std::cout << "Max: " << result << std::endl;
    
    return 0;
}
